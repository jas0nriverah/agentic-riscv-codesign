(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(declare-fun independent_opaque_1 () (_ BitVec 32))
(assert
 (let ((?x983 (bvand (_ bv13 32) (_ bv31 32))))
(let ((?x402 (bvshl independent_opaque_0 ?x983)))
(let ((?x551 (bvadd (bvshl independent_opaque_1 (bvand (_ bv31 32) (_ bv31 32))) independent_opaque_0)))
(let ((?x1180 (bvshl ?x551 ?x983)))
(and (distinct ?x1180 ?x402) true))))))
(check-sat)
