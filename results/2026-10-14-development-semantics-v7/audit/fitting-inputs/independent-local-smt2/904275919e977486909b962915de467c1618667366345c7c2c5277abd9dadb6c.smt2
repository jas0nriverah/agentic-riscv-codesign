(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_2 () (_ BitVec 32))
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x51 (bvadd (bvshl independent_opaque_1 (bvand (_ bv4 32) (_ bv31 32))) (bvshl independent_opaque_2 (bvand (_ bv4 32) (_ bv31 32))))))
(let ((?x305 (bvadd independent_opaque_0 ?x51)))
(let ((?x37 (bvand (_ bv4 32) (_ bv31 32))))
(let ((?x7 (bvadd independent_opaque_0 (bvshl (bvadd independent_opaque_2 independent_opaque_1) ?x37))))
(and (distinct ?x7 ?x305) true))))))
(check-sat)
