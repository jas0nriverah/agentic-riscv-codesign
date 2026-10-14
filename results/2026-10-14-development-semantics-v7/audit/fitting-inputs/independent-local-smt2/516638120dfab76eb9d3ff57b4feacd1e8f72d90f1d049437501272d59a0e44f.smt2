(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x44 (bvadd independent_opaque_0 (bvadd (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32))) (_ bv736 32)))))
(let ((?x28 (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32)))))
(let ((?x37 (bvadd (bvadd independent_opaque_0 (_ bv736 32)) ?x28)))
(and (distinct ?x37 ?x44) true)))))
(check-sat)
