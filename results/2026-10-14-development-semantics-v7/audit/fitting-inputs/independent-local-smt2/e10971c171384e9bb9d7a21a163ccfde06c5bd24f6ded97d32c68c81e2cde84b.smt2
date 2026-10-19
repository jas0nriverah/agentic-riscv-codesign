(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x305 (bvadd (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))) (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv4 32) (_ bv31 32)))))))
(let ((?x113 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x654 (bvshl (bvsub independent_opaque_0 (bvshl independent_opaque_1 ?x113)) ?x113)))
(and (distinct ?x654 ?x305) true)))))
(check-sat)
