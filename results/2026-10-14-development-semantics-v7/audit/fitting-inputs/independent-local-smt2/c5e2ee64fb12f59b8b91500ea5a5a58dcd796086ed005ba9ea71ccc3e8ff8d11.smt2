(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x15 (bvadd independent_opaque_0 (bvadd (bvshl independent_opaque_1 (bvand (_ bv13 32) (_ bv31 32))) (_ bv3 32)))))
(let ((?x37 (bvshl independent_opaque_1 (bvand (_ bv13 32) (_ bv31 32)))))
(let ((?x78 (bvadd (bvadd independent_opaque_0 ?x37) (_ bv3 32))))
(and (distinct ?x78 ?x15) true)))))
(check-sat)
