(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_2 () (_ BitVec 32))
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x222 (bvadd (bvshl independent_opaque_1 (bvand (_ bv7 32) (_ bv31 32))) (bvsub (_ bv0 32) (bvshl independent_opaque_2 (bvand (_ bv7 32) (_ bv31 32)))))))
(let ((?x402 (bvadd independent_opaque_0 ?x222)))
(let ((?x573 (bvand (_ bv7 32) (_ bv31 32))))
(let ((?x1210 (bvadd independent_opaque_0 (bvshl (bvsub independent_opaque_1 independent_opaque_2) ?x573))))
(and (distinct ?x1210 ?x402) true))))))
(check-sat)
