(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x85 (bvshl y (_ bv4 32))))
(let ((?x81 (bvshl x (_ bv4 32))))
(let ((?x86 (bvadd ?x81 ?x85)))
(let ((?x19 (bvadd x y)))
(let ((?x84 (bvshl ?x19 (_ bv4 32))))
(and (distinct ?x84 ?x86) true)))))))
(check-sat)
