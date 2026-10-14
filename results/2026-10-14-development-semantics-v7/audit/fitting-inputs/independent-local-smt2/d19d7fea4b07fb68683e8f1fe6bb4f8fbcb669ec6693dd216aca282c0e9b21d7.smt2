(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x72 (bvadd (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))) independent_opaque_1)))
(let ((?x52 (bvadd ?x72 (bvadd (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32))) (_ bv81 32)))))
(let ((?x424 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x66 (bvadd (bvshl (bvadd independent_opaque_0 independent_opaque_1) ?x424) independent_opaque_1)))
(let ((?x24 (bvadd ?x66 (_ bv81 32))))
(and (distinct ?x24 ?x52) true)))))))
(check-sat)
